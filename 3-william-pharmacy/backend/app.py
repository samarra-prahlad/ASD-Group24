from flask import Flask, request
from flask_cors import CORS
from openai import OpenAI
from pathlib import Path
import os
import requests

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


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()

@app.get("/medications")
def get_medications():
    try:
        response = requests.get(f"{DATABASE_URL}/medications")
        response.raise_for_status()
        print(f"Retrieved medications: {response.json()}")
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching medications: {e}")
        return []

@app.get("/prescriptions/<patient_id>")
def get_prescriptions(patient_id):
    try:
        response = requests.get(f"{DATABASE_URL}/prescriptions/{patient_id}")
        response.raise_for_status()
        print(f"Retrieved prescriptions for patient {patient_id}: {response.json()}")
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching prescriptions for patient {patient_id}: {e}")
        return []


@app.route("/ask", methods=["POST"])
def ask_local_agent():
    question = request.form.get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise software engineering assistant. "
                        "Answer in one short paragraph unless asked otherwise."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            max_tokens=200,
            temperature=0.2,
        )

        answer = response.choices[0].message.content

        return f"<p>{answer}</p>"

    except Exception as exc:
        return (
            "<p>Local AI agent request failed. "
            "Check that Ollama is running and that qwen2.5:0.5b is installed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )


@app.route("/ask-with-context", methods=["POST"])
def ask_with_context():
    question = request.form.get("question", "").strip()

    if not question:
        return "<p>Question is required.</p>", 400


    loaded_system_prompt = load_prompt("implementation_system_prompt.txt")
    loaded_task_prompt = load_prompt("context_qa_task_prompt.txt")


    final_prompt = loaded_task_prompt + "\n\n" + question


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
            temperature=0.0,
        )

        answer = response.choices[0].message.content
        return f"<p>{answer}</p>"
    
    except Exception as exc:
        return (
            "<p>Context-aware request failed. "
            "Check that Ollama is running and that qwen2.5:0.5b is installed.</p>"
            f"<pre>{exc}</pre>",
            503,
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=True)