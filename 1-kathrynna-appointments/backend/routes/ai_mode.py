from flask import Blueprint, request, jsonify

from ai.agent import run as run_agent


ai_mode_bp = Blueprint(
    "ai_mode",
    __name__
)


@ai_mode_bp.post("/chat")
def ai_chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = data.get(
        "message",
        ""
    )

    if isinstance(message, str):
        message = message.strip()
    else:
        message = ""

    patient_id = data.get(
        "patientId"
    )

    history = data.get(
        "history",
        []
    )

    role = data.get(
        "role",
        "patient"
    )

    if role not in (
        "patient",
        "admin"
    ):
        role = "patient"

    if not message:

        return jsonify({
            "error": "Message is required."
        }), 400

    try:

        result = run_agent(
            message,
            patient_id=patient_id,
            history=history,
            role=role
        )

        return jsonify({
            "reply": result["reply"]
        }), 200

    except Exception as exc:

        print(
            f"[ai_mode] chat request failed: {exc}"
        )

        return jsonify({
            "error": (
                "AI assistant failed. "
                f"{str(exc)}"
            )
        }), 503