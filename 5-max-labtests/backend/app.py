import os
import re
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://labtests-database:6005")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
SHARED_DATABASE_URL = os.getenv("SHARED_DATABASE_URL", "http://shared-database:6000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")


@app.get("/")
def health():
    return jsonify({"service": "labtests-backend", "status": "running"})


@app.get("/orders")
def get_orders():
    r = requests.get(f"{DATABASE_SERVICE_URL}/orders", timeout=5)
    return jsonify(r.json())


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


def flag_result_with_ai(result_value, reference_range):
    prompt = (
        f"Lab result: {result_value}\n"
        f"Reference range: {reference_range}\n\n"
        "Task: decide if this result is abnormal given the reference range.\n"
        "Respond in exactly this format, two lines, no extra text:\n"
        "VERDICT: YES or NO\n"
        "REASON: one short sentence explaining why"
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
    data = request.get_json()
    user_message = data.get("message", "")

    prompt = (
        "You are a helpful assistant for a hospital lab tests system. "
        "Answer questions about lab tests, results, and general lab process. "
        "Keep answers short and clear.\n\n"
        f"User: {user_message}"
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
        reply = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        reply = f"Chat unavailable: {exc}"

    return jsonify({"reply": reply})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)