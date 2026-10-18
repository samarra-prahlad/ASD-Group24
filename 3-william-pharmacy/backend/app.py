from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path
import os
import requests
from mcp_client import call_check_stock
from rag_client import call_answer_question
import difflib

DATABASE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://localhost:6003")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
PROMPT_DIR = Path(__file__).with_name("prompts")

app = Flask(__name__)
CORS(app)

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)


SHARED_ACCESS_API_URL = os.environ.get("SHARED_ACCESS_API_URL", "http://shared-backend:5000")

@app.get("/session/role")
def session_role():
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "token is required"}), 400

    try:
        resp = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=5,
        )
    except requests.RequestException:
        return jsonify({"error": "auth service unavailable"}), 502

    if resp.status_code != 200:
        return jsonify({"valid": False}), 401

    data = resp.json()
    return jsonify({
        "valid": True,
        "role": data["role"],
        "first_name": data["first_name"],
    })



def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()

def proxy(method, path, **kwargs):
    """Forward a request to the database service and pass back its response as-is."""
    try:
        response = requests.request(method, f"{DATABASE_URL}{path}", timeout=10, **kwargs)
    except requests.RequestException as e:
        print(f"Error calling database service ({method} {path}): {e}")
        return jsonify({"error": "database service unavailable"}), 502

    # Forward whatever the database service returned — success or error —
    # instead of swallowing it and returning a generic response.
    try:
        body = response.json()
    except ValueError:
        body = {"error": "invalid response from database service"}
    return jsonify(body), response.status_code


# --- read endpoints (existing, fixed to forward real status codes) --------

@app.get("/medications")
def get_medications():
    return proxy("GET", "/medications")


@app.get("/prescriptions/<patient_id>")
def get_prescriptions(patient_id):
    return proxy("GET", f"/prescriptions/{patient_id}")


# --- admin: medications -----------------------------------------------

@app.post("/admin/medications")
def add_medication():
    return proxy("POST", "/admin/medications/", json=request.get_json(silent=True) or {})


@app.put("/admin/medications/<int:med_id>")
def update_medication(med_id):
    return proxy("PUT", f"/admin/medications/{med_id}", json=request.get_json(silent=True) or {})


@app.delete("/admin/medications/<int:med_id>")
def delete_medication(med_id):
    return proxy("DELETE", f"/admin/medications/{med_id}")


# --- admin: prescriptions -----------------------------------------------

@app.post("/admin/prescriptions")
def create_prescription():
    return proxy("POST", "/admin/prescriptions", json=request.get_json(silent=True) or {})


@app.put("/admin/prescriptions/<int:prescription_id>")
def update_prescription(prescription_id):
    return proxy("PUT", f"/admin/prescriptions/{prescription_id}", json=request.get_json(silent=True) or {})


@app.delete("/admin/prescriptions/<int:prescription_id>")
def delete_prescription(prescription_id):
    return proxy("DELETE", f"/admin/prescriptions/{prescription_id}")



# AI chatbot endpoints

def find_medication_in_question(question: str) -> str | None:
    try:
        resp = requests.get(f"{DATABASE_URL}/medications", timeout=5)
        resp.raise_for_status()
        medications = resp.json()
    except requests.RequestException:
        return None

    question_lower = question.lower()

    # map each drug's base name (first word) back to its full name
    base_name_map = {}
    for m in medications:
        name = m.get("name", "")
        if name:
            base_name_map[name.split()[0].lower()] = name

    # 1. direct substring match first — cheap and exact
    for base, full_name in base_name_map.items():
        if base in question_lower:
            return full_name

    # 2. fuzzy fallback — catches typos like "amoxicilin" -> "amoxicillin"
    for word in question_lower.split():
        close = difflib.get_close_matches(word, base_name_map.keys(), n=1, cutoff=0.75)
        if close:
            return base_name_map[close[0]]

    return None


@app.route("/ask-mcp", methods=["POST"])
def ask_mcp():
    question = request.form.get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400

    medication_name = find_medication_in_question(question)
    if not medication_name:
        return (
            "<p>Couldn't identify a medication in your question. "
            "Try including the drug name, e.g. 'is amoxicillin in stock?'</p>",
            400,
        )

    try:
        stock_result = call_check_stock(medication_name)
    except Exception as exc:
        # network/connection failure to the MCP server itself
        return (
            "<p>Couldn't reach the MCP server. Is it running on port 7000?</p>"
            f"<pre>{exc}</pre>",
            503,
        )

    if "error" in stock_result:
        # tool ran fine, but reported a problem (e.g. pharmacy-backend down, not found)
        return f"<p>{stock_result['error']}</p>", 404

    loaded_system_prompt = load_prompt("implementation_system_prompt.txt")
    final_prompt = (
        f"Verified stock data: {stock_result}\n\n"
        f"Using only this verified data, answer the question: {question}"
    )

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": loaded_system_prompt},
                {"role": "user", "content": final_prompt}
            ],
            max_tokens=200,
            temperature=0.0,
        )
        answer = response.choices[0].message.content
        return f"<p>{answer}</p>"

    except Exception as exc:
        return (
            "<p>MCP-grounded request failed. "
            "Check that Ollama is running and that qwen2.5:0.5b is installed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )


@app.route("/ask-rag", methods=["POST"])
def ask_rag():
    question = request.form.get("question", "").strip()
    if not question:
        return "<p>Question is required.</p>", 400

    try:
        result = call_answer_question(question)
    except Exception as exc:
        return f"<p>RAG request failed.</p><pre>{exc}</pre>", 503

    if result["status"] == "insufficient_context":
        return (
            f"<p>{result['answer']}</p>"
            f"<p><em>Confidence: {result['confidence_category']}</em></p>"
        )

    citations_html = "".join(f"<li>{c['source_id']}</li>" for c in result["citations"])
    return (
        f"<p>{result['answer']}</p>"
        f"<p><em>Confidence: {result['confidence_category']}</em></p>"
        f"<ul>{citations_html}</ul>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=True)