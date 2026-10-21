"""Planner agent: creates the workflow plan and identifies the evidence the Worker needs."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from agents.common import load_prompt, step_result  # noqa: E402


def plan_workflow(user_request, feature, evidence, llm):
    fields = sorted({key for record in evidence if isinstance(record, dict) for key in record})
    user_prompt = (
        f"Feature: {feature}\n"
        f"User request: {user_request}\n"
        f"Evidence available: {len(evidence)} record(s) with fields: {', '.join(fields) or 'none'}"
    )
    text, error = llm(config.PLANNER_MODEL, load_prompt("planner_prompt.txt"), user_prompt)
    return step_result(config.PLANNER_MODEL, text, error)


if __name__ == "__main__":
    import json
    import llm_client

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "sample_evidence", "billing.json")) as f:
        sample = json.load(f)
    result = plan_workflow("Summarise outstanding invoices for patient 1.", "billing", sample, llm_client.chat)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "completed" else 1)
