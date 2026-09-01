import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://labtests-database:6005")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
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
        v = requests.get(f"{SHARED_ACCESS_API_URL}/validate", params={"patient_id": patient_id}, timeout=5)
        if v.status_code != 200 or not v.json().get("valid"):
            return jsonify({"error": "Invalid patient_id"}), 400
    except requests.RequestException as exc:
        return jsonify({"error": "Shared access API unavailable", "detail": str(exc)}), 503

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
        f"Reference range: {reference_range}\n"
        "Is this result abnormal? Reply with exactly 'YES' or 'NO' on the first line, "
        "then a one-sentence reason on the second line."
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
        lines = text.split("\n", 1)
        flagged = 1 if lines[0].strip().upper().startswith("YES") else 0
        ai_notes = lines[1].strip() if len(lines) > 1 else ""
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)