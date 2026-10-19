"""Shared non-containerised Multi-Agent Server (port 7002)."""
from flask import Flask, jsonify, request

import config
import llm_client
from coordinator import (AWAITING, DECISIONS, Coordinator, InvalidDecision, WorkflowNotFound,
                         WorkflowStateError)
from store import WorkflowStore


def create_app(coordinator=None):
    app = Flask(__name__)
    coord = coordinator or Coordinator(llm_client.chat, WorkflowStore(config.DATA_DIR))

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "service": "multi-agent-server",
            "agents": ["planner", "worker", "reviewer"],
            "models": {"planner": config.PLANNER_MODEL, "worker": config.WORKER_MODEL,
                       "reviewer": config.REVIEWER_MODEL},
            "decisions": list(DECISIONS),
        })

    @app.post("/workflow")
    def start_workflow():
        data = request.get_json(silent=True) or {}
        user_request = data.get("user_request")
        if not isinstance(user_request, str) or not user_request.strip():
            return jsonify({"error": "user_request is required"}), 400
        feature = data.get("feature", "general")
        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "feature must be a non-empty string"}), 400
        evidence = data.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(r, dict) for r in evidence):
            return jsonify({"error": "evidence must be a list of objects"}), 400

        workflow = coord.run(user_request.strip(), feature.strip(), evidence, data.get("requested_by"))
        return jsonify(workflow), (201 if workflow["status"] == AWAITING else 503)

    @app.get("/workflow/<workflow_id>")
    def get_workflow(workflow_id):
        workflow = coord.get(workflow_id)
        if workflow is None:
            return jsonify({"error": "workflow not found"}), 404
        return jsonify(workflow)

    @app.post("/workflow/<workflow_id>/review")
    def review_workflow(workflow_id):
        data = request.get_json(silent=True) or {}
        try:
            workflow = coord.review(workflow_id, data.get("decision"), data.get("reviewer"),
                                    data.get("notes", ""), data.get("correction"))
        except WorkflowNotFound:
            return jsonify({"error": "workflow not found"}), 404
        except InvalidDecision as exc:
            return jsonify({"error": str(exc)}), 400
        except WorkflowStateError as exc:
            return jsonify({"error": str(exc)}), 409
        return jsonify(workflow)

    @app.get("/workflows")
    def list_workflows():
        try:
            limit = max(1, min(int(request.args.get("limit", 20)), 100))
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
        return jsonify({"workflows": coord.list(feature=request.args.get("feature"), limit=limit)})

    return app


if __name__ == "__main__":
    print("Starting Group24 Shared Multi-Agent Server...")
    print(f"Server status: RUNNING on http://{config.HOST}:{config.PORT}")
    print(f"Planner={config.PLANNER_MODEL} Worker={config.WORKER_MODEL} Reviewer={config.REVIEWER_MODEL}")
    create_app().run(host=config.HOST, port=config.PORT, debug=False)
